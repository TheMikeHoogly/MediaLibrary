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


def _corps(nom):
    """La fonction SANS sa docstring. Un banc juge du code, pas une prose :
    la docstring de `remplir_file_retag` raconte la panne qu elle corrige et
    y cite forcement `rglob` et `cur`."""
    n = _noeud(nom)
    corps = n.body[1:] if (n.body and isinstance(n.body[0], ast.Expr)
                           and isinstance(n.body[0].value, ast.Constant)
                           and isinstance(n.body[0].value.value, str)) else n.body
    return "\n".join(ast.get_source_segment(SOURCE, x) or "" for x in corps)


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

    def test_selection_sous_cible_et_bornee(self):
        s = _src("remplir_file_retag")
        self.assertIn("TAG_QUEUE.qsize() >= RETAG_LOT", s)
        self.assertIn("cles_a_retaguer", s)
        # borne du lot : la file est en memoire
        self.assertIn("lot=RETAG_LOT", s)

    def test_index_jamais_vide_par_la_campagne(self):
        # Le remplissage n'appelle PAS remove_many : la photo reste visible,
        # nommee et cherchable pendant les jours que dure la campagne.
        self.assertNotIn("remove_many", _src("remplir_file_retag"))

    def test_le_lot_ne_depend_pas_du_scan_approfondi(self):
        # Il en dependait : un cycle sur douze, ~90 min, alors qu un lot de 500
        # se consomme en ~2 h. Nuit du 05 au 06/09 : trois lots entre 20:00 et
        # 00:17, file VIDE a 00:47, GPU au repos en pleine campagne.
        self.assertNotIn("deep", _corps("remplir_file_retag"))


class UnEchecNeCoutePasLaPhoto(unittest.TestCase):
    def setUp(self):
        self.s = _src("tagger_worker")

    def test_chaque_sortie_d_echec_est_gardee(self):
        # L invariant n est PAS « il y a trois sorties » -- il y en avait trois,
        # une quatrieme est arrivee le 06/09 (contenu perdu) et ce test est
        # devenu rouge pour une raison qui n etait pas un defaut. L invariant,
        # c est que CHAQUE `_marquer_echec` du worker soit precede de la garde
        # retag : ecrit ainsi, il tient encore a la cinquieme.
        n_marquer = self.s.count("_marquer_echec(name")
        n_garde = self.s.count("if not (retag and _echec_retag(name")
        self.assertGreaterEqual(n_marquer, 3)
        self.assertEqual(n_marquer, n_garde,
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


class LeNasNEstPasParcouruEnBoucle(unittest.TestCase):
    """Audit O13, mesure du 05/09 : le `rglob` d une racine NAS (44 876
    fichiers sur SMB) prend 7 a 9 minutes, et il tournait a CHAQUE cycle de
    5 minutes -- donc en continu, sans jamais finir avant le suivant, et en
    silence. Pendant la campagne de retag il disputait au tagueur la seule
    ressource dont celui-ci a besoin."""

    def test_cadence_nas_separee_et_multiple_du_scan_approfondi(self):
        self.assertIn("NAS_SCAN_CYCLES = 6", SOURCE)
        # 12 % 6 == 0 : un cycle approfondi tombe toujours sur un tour NAS.
        self.assertEqual(12 % 6, 0)

    def test_le_scan_sait_sauter_les_racines_nas(self):
        s = _src("scan_uploads")
        self.assertIn("nas=True", s)
        self.assertIn("if not nas:", s)
        # ... mais JAMAIS Uploads, qui est local et court.
        self.assertLess(s.index('_sync_dir("Uploads"'), s.index("if not nas:"))

    def test_un_cycle_approfondi_implique_le_nas(self):
        # Sinon la passe des modifies et le lot de retag sauteraient un tour
        # sur deux sans que rien ne le dise.
        self.assertIn("nas = first or deep or (cycle % NAS_SCAN_CYCLES == 0)",
                      SOURCE)

    def test_l_enumeration_se_dit_a_chaque_fois(self):
        # Elle ne se disait qu'au demarrage : c'est ce qui l'a rendue invisible.
        s = _src("scan_uploads")
        self.assertIn("image(s) énumérée(s) en", s)


class LaCampagneNeJeunePasApresUnRedemarrage(unittest.TestCase):
    def test_premier_cycle_approfondi_si_campagne_active(self):
        # Le protocole impose un redemarrage pour livrer tout changement de
        # server.py. Si le premier cycle n etait pas approfondi, chaque
        # livraison couterait une demi-heure de GPU inoccupe -- environ une
        # journee sur une campagne de cinq jours.
        self.assertIn(
            "(cycle % 12 == 6) or (cycle == 0 and retag_cible() is not None)",
            SOURCE)


class LaFileNeDependPasDuNas(unittest.TestCase):
    """Le defaut du 06/09 : file videe a 11h34, GPU a 0 % jusqu a 13h.

    Le remplissage vivait dans `_sync_dir`, appelee APRES un `rglob` de 44 000
    fichiers sur SMB (632 s a 1 473 s selon la charge ; plus de 85 minutes le
    jour ou une passe de maintenance et 2 139 vignettes sont tombees dessus).
    Rien ne cassait : le GPU attendait, simplement. C est le pire genre de
    panne -- celle qui ressemble a du calme.
    """

    def test_le_remplissage_est_une_fonction_a_lui(self):
        self.assertTrue(_src("remplir_file_retag"))

    def test_il_ne_lit_jamais_le_disque(self):
        s = _corps("remplir_file_retag")
        for interdit in ("rglob", "iterdir", "glob(", "Path(", "stat(",
                         "exists()", "_stat_of", "cur"):
            self.assertNotIn(interdit, s,
                             f"« {interdit} » remet le disque dans le chemin "
                             "du remplissage : c est la panne du 06/09.")

    def test_il_lit_l_index_en_memoire(self):
        self.assertIn("STORE.data.items()", _corps("remplir_file_retag"))

    def test_appele_avant_toute_enumeration(self):
        s = _corps("scan_uploads")
        self.assertIn("remplir_file_retag()", s)
        self.assertLess(s.index("remplir_file_retag()"), s.index("rglob"),
                        "Le remplissage doit passer AVANT le premier rglob.")

    def test_le_bloc_a_quitte_sync_dir(self):
        # Deux endroits qui enfilent, c est deux regles qui divergeront.
        self.assertNotIn("cles_a_retaguer", _src("_sync_dir"))

    def test_plafond_de_file_conserve(self):
        # Enfiler les 40 000 cles ferait un etat qu un redemarrage perdrait.
        self.assertIn("TAG_QUEUE.qsize() >= RETAG_LOT",
                      _corps("remplir_file_retag"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
