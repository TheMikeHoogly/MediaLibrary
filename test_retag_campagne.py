#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests du CABLAGE de la campagne de retag (chantier 2 quater) -- SUR LE CODE
DE PROD, sans importer `server.py` (torch, insightface, et surtout photos.db,
que la VM ne sait pas ouvrir).

La logique PURE (le levier, la selection des cles) est testee ailleurs, dans
`test_tagging_meta.py`. Ici on prouve les quatre choses que le cablage peut
perdre en silence a la prochaine retouche, et qui coutent des donnees :

1. **Le fichier ABSENT ne fait rien.** Le levier est `retag_actif.txt` ; la
   selection ne tourne que sous `if deep` et `if cible`.
2. **Un retag n'ecrase JAMAIS une entree par un `failed`.** `_marquer_echec`
   remplace l'entree par {failed: True} : sur une photo deja taguee, ce serait
   perdre ses mots-cles, sa date et son GPS pour un timeout d'Ollama. Les TROIS
   sorties d'echec du worker passent d'abord par `_echec_retag`.
3. **Un retag reussi COMPLETE l'entree, il ne la remplace pas** : ce que la
   passe n'a pas recalcule (date, GPS, import) survit.
4. **La detection prealable ne re-detecte jamais** une entree deja presente --
   un cluster deja nomme ne doit pas etre rompu (invariant n. 1) -- et passe par
   l'ordonnanceur existant (`creneau`), pas par une 5e politique GPU (n. 4).
"""

import ast
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / "server.py").read_text(encoding="utf-8")
ARBRE = ast.parse(SOURCE)


def _noeud(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return n
    raise AssertionError(nom + " introuvable dans server.py")


def _src(nom):
    return ast.get_source_segment(SOURCE, _noeud(nom)) or ""


class LevierAbsentNeFaitRien(unittest.TestCase):
    def test_fichier_bascule_declare(self):
        self.assertIn('RETAG_FICHIER = SCRIPT_DIR / "retag_actif.txt"', SOURCE)

    def test_levier_jamais_livre_dans_le_depot(self):
        # Le levier ne se livre PAS : sa seule presence DEMARRE le re-tagging
        # de tout le fonds. Premiere version de ce test : elle verifiait que le
        # fichier n'existe pas sur le disque -- mais le dossier de travail EST
        # l'installation vivante, et le test est devenu rouge la seconde ou
        # Mike a lance la campagne, pour une raison qui n'etait pas un defaut.
        # Ce qu'il faut prouver, c'est que git ne le prendra jamais.
        ignore = (HERE / ".gitignore").read_text(encoding="utf-8")
        lignes = [l.strip() for l in ignore.splitlines()]
        self.assertIn("retag_actif.txt", lignes,
                      "retag_actif.txt doit etre dans .gitignore : c'est de "
                      "l'etat machine, jamais de la source")

    def test_cible_none_si_fichier_absent(self):
        s = _src("retag_cible")
        self.assertIn("except OSError", s)
        self.assertIn("version_retag", s)

    def test_cible_etrangere_refusee(self):
        # Une cible qui n est pas la version du code ferait re-taguer le fonds
        # a CHAQUE scan sans qu aucun compteur baisse : le worker estampille
        # TAGGING_PIPELINE_VERSION, jamais ce qui est ecrit dans le fichier.
        s = _src("retag_cible")
        self.assertIn("cible != TAGGING_PIPELINE_VERSION", s)
        self.assertIn("return None", s.split("cible != TAGGING_PIPELINE_VERSION")[1])

    def test_refus_visible_dans_l_api(self):
        s = _src("_retag_etat")
        self.assertIn("_RETAG_REFUS_DIT", s)
        self.assertIn("'refus'", s)

    def test_selection_sous_scan_approfondi_et_cible(self):
        s = _src("_sync_dir")
        self.assertIn("if deep and TAG_QUEUE.qsize() < RETAG_LOT:", s)
        self.assertIn("cles_a_retaguer", s)
        # borne du lot : la file est en memoire
        self.assertIn("lot=RETAG_LOT", s)

    def test_index_jamais_vide_par_la_campagne(self):
        # Le bloc de retag n'appelle PAS remove_many : la photo reste visible.
        s = _src("_sync_dir")
        bloc = s.split("# 2 bis)")[1].split("# 3)")[0]
        self.assertNotIn("remove_many", bloc)

    def test_retag_enfile_avant_la_passe_des_modifies(self):
        # La passe des « fichiers modifies » fait un stat sur CHAQUE fichier de
        # la racine (44 876 sur le NAS, plusieurs minutes). Le bloc de retag ne
        # touche QUE la memoire : le faire attendre derriere, c'est laisser le
        # GPU vider sa file et s'arreter. Observe le 05/09.
        s = _src("_sync_dir")
        self.assertLess(s.index("# 2 bis)"), s.index("# 3) fichiers modifi"),
                        "le retag doit enfiler AVANT la passe des modifies")


class UnEchecNeCoutePasLaPhoto(unittest.TestCase):
    def setUp(self):
        self.s = _src("tagger_worker")

    def test_les_trois_sorties_d_echec_sont_gardees(self):
        # Chaque `_marquer_echec` du worker est precede de la garde retag.
        n_marquer = self.s.count("_marquer_echec(name")
        n_garde = self.s.count("if not (retag and _echec_retag(name")
        self.assertEqual(n_marquer, 3, "3 sorties d'echec attendues")
        self.assertEqual(n_garde, 3,
                         "chaque sortie d'echec doit passer par _echec_retag")

    def test_retag_defini_avant_le_try(self):
        # Sinon les gestionnaires d'exception lisent une variable inexistante.
        avant = self.s.split("try:")[0]
        self.assertIn("retag = False", avant)

    def test_echec_retag_conserve_l_entree(self):
        s = _src("_echec_retag")
        self.assertIn("e['retag_fail']", s)
        self.assertNotIn("'failed': True", s)
        self.assertNotIn("STORE.remove", s)

    def test_anti_boucle_sur_la_cible(self):
        # La marque d'abandon porte la CIBLE : un bump la rend candidate a
        # nouveau, mais un scan de plus ne la represente pas.
        self.assertIn("retag_fail", (HERE / "tagging_meta.py").read_text(
            encoding="utf-8"))


class UnRetagCompleteLEntree(unittest.TestCase):
    def test_base_conservee_puis_mise_a_jour(self):
        s = _src("tagger_worker")
        self.assertIn("base = dict(STORE.data.get(name) or {})", s)
        self.assertIn("base.update(entry)", s)

    def test_marques_d_echec_effacees_au_succes(self):
        s = _src("tagger_worker")
        for cle in ("'failed'", "'error'", "'retag_fail'", "'retag_error'"):
            self.assertIn(cle, s.split("base = dict(")[1].split("base.update")[0])

    def test_store_has_contourne_seulement_en_retag(self):
        s = _src("tagger_worker")
        self.assertIn("(STORE.has(name) and not retag)", s)


class LaDetectionNeRompsPasUnCluster(unittest.TestCase):
    def setUp(self):
        self.s = _src("_detecter_avant_retag")

    def test_jamais_de_re_detection(self):
        self.assertIn("fe = FACE_STORE.get(key)", self.s)
        self.assertIn("ae = ANIMAL_STORE.get(key)", self.s)
        self.assertIn("fe is None or _is_transient_io_fail(fe)", self.s)
        self.assertIn("ae is None or _is_transient_io_fail(ae)", self.s)

    def test_passe_par_l_ordonnanceur_existant(self):
        self.assertIn("creneau('visages'", self.s)
        self.assertIn("creneau('animaux'", self.s)

    def test_n_echoue_jamais_vers_l_appelant(self):
        # Deux try/except larges : le tagging prime sur la detection.
        self.assertEqual(self.s.count("except Exception as e:"), 2)

    def test_appelee_avant_les_assertions(self):
        w = _src("tagger_worker")
        i_det = w.index("_detecter_avant_retag(name, path)")
        i_ass = w.index("_assertions_pour(name")
        i_oll = w.index("ollama_generate(")
        self.assertLess(i_det, i_ass)
        self.assertLess(i_ass, i_oll)


class LaCampagneNeJeunePasApresUnRedemarrage(unittest.TestCase):
    def test_premier_cycle_approfondi_si_campagne_active(self):
        # Le protocole impose un redemarrage pour livrer tout changement de
        # server.py. Si le premier cycle n etait pas approfondi, chaque
        # livraison couterait une demi-heure de GPU inoccupe -- environ une
        # journee sur une campagne de cinq jours.
        self.assertIn(
            "(cycle % 12 == 6) or (cycle == 0 and retag_cible() is not None)",
            SOURCE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
