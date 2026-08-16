"""Le garde d'`UPLOAD_DIR` : un DRAPEAU n'est pas un dossier.

Pourquoi ce test existe (14/08/2026) : `server.py` prenait `sys.argv[1]` comme
`UPLOAD_DIR` sans regarder ce que c'etait. Or `server` est IMPORTE par des
outils qui ont leurs propres drapeaux — `eval_tagging.py --depouiller`,
`mesure_repasse.py --limit 50`. L'outil heritait alors d'un `UPLOAD_DIR` egal a
« --depouiller » : un chemin RELATIF, donc un dossier fabrique dans le dossier
du projet, et un scan d'uploads qui regarde ailleurs que le NAS. Sans effet
observe (l'echantillon du banc n'a aucune photo d'Uploads) — mais c'est
exactement la forme des trois pannes silencieuses de la session 14.

Le test lance un SOUS-PROCESSUS par cas : l'import de `server` a des effets de
bord (creation de dossiers) qu'on ne veut pas dans le processus de test, et on
veut mesurer le vrai chemin de code, pas une reconstitution.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

# Le fils ecrit son verdict dans un fichier : sur Windows, les avertissements de
# `_creer_dossier_si_absolu` contiennent des caracteres que stdout peut refuser.
ENFANT = r'''
import json, sys
from pathlib import Path
sortie = sys.argv.pop()          # dernier argument = ou ecrire le verdict
import server
Path(sortie).write_text(json.dumps({
    "upload_dir": str(server.UPLOAD_DIR),
    "data_dir": str(server.DATA_DIR),
}), encoding="utf-8")
'''


def _upload_dir_pour(args, encodage_sortie=None):
    """Importe `server` avec `sys.argv[1:] = args` et rend son `UPLOAD_DIR`.

    La sortie du fils est CAPTUREE (un tuyau, jamais une console) : c'est la
    condition qui a fait mourir l'import le 15/08. `encodage_sortie` force en
    plus la page de code du fils, pour rejouer le cas Windows partout.
    """
    env = dict(os.environ)
    env.pop("PYTHONIOENCODING", None)
    env.pop("PYTHONUTF8", None)
    if encodage_sortie:
        env["PYTHONIOENCODING"] = encodage_sortie
        env["PYTHONUTF8"] = "0"
    with tempfile.TemporaryDirectory() as tmp:
        verdict = Path(tmp) / "verdict.json"
        cmd = [sys.executable, "-c", ENFANT] + list(args) + [str(verdict)]
        r = subprocess.run(cmd, cwd=str(SCRIPT_DIR), capture_output=True,
                           text=True, errors="replace", timeout=180, env=env)
        if not verdict.exists():
            raise AssertionError(
                "l'import de server a echoue :\n" + (r.stderr or "")[-2000:])
        return json.loads(verdict.read_text(encoding="utf-8"))


class TestUploadDirArgv(unittest.TestCase):

    def test_drapeau_depouiller_nest_pas_un_dossier(self):
        """`eval_tagging.py --depouiller` : le cas qui a motive le correctif."""
        v = _upload_dir_pour(["--depouiller"])
        self.assertNotEqual(Path(v["upload_dir"]).name, "--depouiller")
        self.assertFalse(v["upload_dir"].startswith("-"))

    def test_drapeau_avec_valeur(self):
        """`--limit 50` : le drapeau ET sa valeur sont ignores comme dossier."""
        v = _upload_dir_pour(["--limit", "50"])
        self.assertFalse(v["upload_dir"].startswith("-"))
        self.assertNotEqual(Path(v["upload_dir"]).name, "--limit")

    def test_sans_argument_repli_inchange(self):
        """Aucun argument : le repli (dossier_uploads.txt / DATA_DIR) tient."""
        v = _upload_dir_pour([])
        self.assertTrue(v["upload_dir"])
        self.assertFalse(v["upload_dir"].startswith("-"))

    def test_drapeau_donne_le_meme_repli_que_sans_argument(self):
        """Le garde ne fait pas autre chose que « comme s'il n'y avait rien ».

        C'est la vraie propriete : un drapeau ne doit pas seulement etre refuse,
        il doit laisser la priorite suivante (dossier_uploads.txt, puis
        DATA_DIR) se derouler a l'identique.
        """
        self.assertEqual(_upload_dir_pour(["--depouiller"])["upload_dir"],
                         _upload_dir_pour([])["upload_dir"])

    def test_import_survit_a_une_sortie_cp1252(self):
        """Une sortie REDIRIGEE ne tue plus l'import (constate le 15/08).

        `python outil.py > sortie.txt` sous Windows : stdout n'est plus une
        console, Python retombe sur cp1252, et le premier pictogramme des
        messages de demarrage leve UnicodeEncodeError A L'IMPORT. On force ici
        la meme page de code, sur n'importe quelle plateforme.
        """
        v = _upload_dir_pour([], encodage_sortie="cp1252")
        self.assertTrue(v["upload_dir"])

    def test_vrai_dossier_toujours_honore(self):
        """Le correctif ne casse pas l'usage documente : un chemin passe."""
        with tempfile.TemporaryDirectory() as tmp:
            cible = Path(tmp) / "uploads_test"
            cible.mkdir()
            v = _upload_dir_pour([str(cible)])
            self.assertEqual(Path(v["upload_dir"]).resolve(), cible.resolve())


if __name__ == "__main__":
    unittest.main(verbosity=2)
