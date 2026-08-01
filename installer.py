#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Installateur du projet MediaLibrary — nouveau PC, en une commande.

Reconstruit tout ce que `git clone` ne porte pas : l'environnement Python isole
(.venv), les dependances des pipelines IA, le modele Ollama, la config, et
(optionnel) le demarrage automatique. Idempotent : relancable sans risque.

Etapes :
  1. Verifie Python (>= 3.10).
  2. Cree .venv si absent.
  3. Installe torch (build CUDA si GPU detecte, sinon CPU) EN PREMIER, puis
     onnxruntime(-gpu), pillow/piexif, puis requirements.txt — dans cet ordre
     pour que pip ne remplace jamais torch CUDA par une build CPU.
  4. `ollama pull` du modele de tagging (modele.txt, defaut qwen3-vl:2b).
  5. Gabarits de config manquants (chemins NAS a renseigner).
  6. Optionnel : --prewarm (pre-telecharge les modeles IA), --autostart (lance le
     serveur a l'ouverture de session Windows).
  7. Bilan de sante (identique a `--check`).

Les modeles InsightFace/YOLO/DINOv2/SigLIP se telechargent au 1er lancement du
serveur si non pre-charges. La base d'index et la config viennent, elles, de
`migrer.py` (etat de l'ancien PC).

Usage :
    python installer.py                 # installation complete (auto GPU/CPU)
    python installer.py --gpu | --cpu   # forcer le choix du moteur
    python installer.py --prewarm       # + pre-telecharger les modeles
    python installer.py --autostart     # + demarrage auto a l'ouverture de session
    python installer.py --check         # doctor : verifie une install existante
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent
IS_WIN = platform.system() == 'Windows'
VENV = RACINE / '.venv'
VPY = VENV / ('Scripts/python.exe' if IS_WIN else 'bin/python')
TORCH_CUDA_INDEX = 'https://download.pytorch.org/whl/cu130'
START_BAT = '0 - Démarrer le serveur.bat'

OK, KO, WARN = '[ OK ]', '[FAIL]', '[ .. ]'
_report = []


def say(status, msg):
    line = f"  {status} {msg}"
    print(line)
    _report.append((status, msg))


def run(cmd, **kw):
    print("   $ " + (cmd if isinstance(cmd, str) else ' '.join(map(str, cmd))))
    return subprocess.run(cmd, **kw).returncode


def modele_tagging():
    f = RACINE / 'modele.txt'
    try:
        for l in f.read_text(encoding='utf-8').splitlines():
            l = l.split('#')[0].strip()
            if l:
                return l
    except OSError:
        pass
    return 'qwen3-vl:2b'


def gpu_present():
    if shutil.which('nvidia-smi'):
        try:
            return subprocess.run(['nvidia-smi'], capture_output=True).returncode == 0
        except Exception:
            return False
    return False


# ── etapes d'installation ─────────────────────────────────────────────────────

def etape_python():
    v = sys.version_info
    if (v.major, v.minor) < (3, 10):
        say(KO, f"Python {v.major}.{v.minor} — il faut 3.10+ (installe-le puis relance)")
        return False
    say(OK, f"Python {v.major}.{v.minor}.{v.micro}")
    return True


def etape_venv():
    if VPY.exists():
        say(OK, ".venv deja present")
        return True
    say(WARN, "creation de .venv…")
    if run([sys.executable, '-m', 'venv', str(VENV)]) != 0 or not VPY.exists():
        say(KO, "echec de creation du .venv")
        return False
    say(OK, ".venv cree")
    return True


def pip(*args):
    return run([str(VPY), '-m', 'pip', 'install', '--disable-pip-version-check', *args])


def etape_deps(gpu):
    run([str(VPY), '-m', 'pip', 'install', '--quiet', '--disable-pip-version-check',
         '--upgrade', 'pip'])
    # 1) torch EN PREMIER (protege la build CUDA d'un remplacement par transitivite)
    if gpu:
        say(WARN, "torch build CUDA (cu130, ~2,5 Go)…")
        if pip('torch', '--index-url', TORCH_CUDA_INDEX) != 0:
            pip('torch', '--extra-index-url', TORCH_CUDA_INDEX)
    else:
        say(WARN, "torch build CPU…")
        pip('torch')
    # 2) onnxruntime : GPU si dispo, repli CPU
    if gpu:
        if pip('onnxruntime-gpu') != 0:
            say(WARN, "onnxruntime-gpu indisponible -> repli CPU")
            pip('onnxruntime')
    else:
        pip('onnxruntime')
    # 3) images + 4) le reste (torch deja satisfait : pip n'y touche pas)
    pip('pillow', 'pillow-heif', 'piexif')
    rc = pip('-r', str(RACINE / 'requirements.txt'))
    say(OK if rc == 0 else KO, "dependances des pipelines (requirements.txt)")
    return rc == 0


def etape_ollama(skip):
    if skip:
        say(WARN, "ollama : saute (--no-ollama)")
        return True
    if not shutil.which('ollama'):
        say(KO, "ollama introuvable — installe Ollama (https://ollama.com) puis relance")
        return False
    m = modele_tagging()
    say(WARN, f"ollama pull {m}…")
    rc = run(['ollama', 'pull', m])
    say(OK if rc == 0 else KO, f"modele de tagging {m}")
    return rc == 0


_CONFIG_TEMPLATES = {
    'dossier_uploads.txt':
        "# Dossier ou le telephone depose ses photos (recu par la page Upload).\n"
        "# Un chemin par ligne (le premier non commente est pris).\n"
        "# Exemple :\n#\\\\NAS-Bremblens\\home\\Photos\\_Uploads\n",
    'dossiers_a_taguer.txt':
        "# Dossiers dont les photos sont analysees par l'IA (un par ligne).\n"
        "# Exemple :\n#\\\\NAS-Bremblens\\home\\Photos\n",
    'dossiers_a_explorer.txt':
        "# Dossiers visibles en lecture dans la page Dossiers (un par ligne).\n"
        "# Exemple :\n#\\\\NAS-Bremblens\\home\\Photos\n",
}


def etape_config():
    cree = 0
    for nom, gabarit in _CONFIG_TEMPLATES.items():
        p = RACINE / nom
        if not p.exists():
            p.write_text(gabarit, encoding='utf-8')
            cree += 1
    if cree:
        say(WARN, f"{cree} gabarit(s) de config cree(s) — a renseigner (chemins NAS) "
                  "si tu n'importes pas l'etat de l'ancien PC")
    else:
        say(OK, "config presente")
    return True


def etape_prewarm():
    say(WARN, "pre-telechargement des modeles IA (peut etre long)…")
    code = (
        "import warnings; warnings.filterwarnings('ignore')\n"
        "try:\n"
        " from insightface.app import FaceAnalysis; FaceAnalysis(name='buffalo_l')\n"
        " print('  insightface OK')\n"
        "except Exception as e: print('  insightface:', e)\n"
        "try:\n"
        " from ultralytics import YOLO; YOLO('yolo11s.pt'); print('  yolo OK')\n"
        "except Exception as e: print('  yolo:', e)\n"
        "try:\n"
        " import timm, torch; timm.create_model('vit_base_patch14_dinov2.lvd142m', pretrained=True); print('  dinov2 OK')\n"
        "except Exception as e: print('  dinov2:', e)\n"
    )
    run([str(VPY), '-c', code])
    say(OK, "pre-chargement termine (voir lignes ci-dessus)")
    return True


def etape_autostart():
    if not IS_WIN:
        say(WARN, "autostart : Windows uniquement")
        return True
    startup = Path(os.environ.get('APPDATA', '')) / \
        'Microsoft/Windows/Start Menu/Programs/Startup'
    lnk = startup / 'MediaLibrary.lnk'
    target = RACINE / START_BAT
    ps = (
        f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
        f"$s.TargetPath='{target}';"
        f"$s.WorkingDirectory='{RACINE}';"
        f"$s.WindowStyle=7;$s.Save()"
    )
    rc = run(['powershell', '-NoProfile', '-Command', ps])
    say(OK if rc == 0 else KO,
        "demarrage auto a l'ouverture de session" if rc == 0 else "echec du raccourci")
    return rc == 0


# ── doctor ────────────────────────────────────────────────────────────────────

def doctor():
    print("\n== Bilan de sante ==")
    if not VPY.exists():
        say(KO, ".venv absent — lance l'installation")
        return
    checks = [
        ("numpy", "import numpy"),
        ("opencv", "import cv2"),
        ("Pillow", "import PIL"),
        ("insightface", "import insightface"),
        ("ultralytics (YOLO)", "import ultralytics"),
        ("timm (DINOv2)", "import timm"),
        ("open_clip (SigLIP)", "import open_clip"),
        ("transformers", "import transformers"),
    ]
    for nom, code in checks:
        rc = subprocess.run([str(VPY), '-c', code], capture_output=True).returncode
        say(OK if rc == 0 else KO, nom)
    # torch + CUDA
    r = subprocess.run(
        [str(VPY), '-c', "import torch;print(torch.__version__, torch.version.cuda,"
         "torch.cuda.is_available())"], capture_output=True, text=True)
    if r.returncode == 0:
        say(OK, "torch " + r.stdout.strip() + "  (version, cuda, dispo)")
    else:
        say(KO, "torch absent")
    # onnxruntime providers
    r = subprocess.run(
        [str(VPY), '-c', "import onnxruntime as o;print(','.join(o.get_available_providers()))"],
        capture_output=True, text=True)
    say(OK if r.returncode == 0 else KO, "onnxruntime providers : " + r.stdout.strip())
    # ollama + modele
    if shutil.which('ollama'):
        m = modele_tagging()
        r = subprocess.run(['ollama', 'list'], capture_output=True, text=True)
        say(OK if m.split(':')[0] in r.stdout else WARN,
            f"ollama present, modele {m} " + ("trouve" if m.split(':')[0] in r.stdout else "A TIRER"))
    else:
        say(KO, "ollama introuvable")
    # etat
    say(OK if (RACINE / 'photos.db').exists() else WARN,
        "photos.db " + ("present" if (RACINE / 'photos.db').exists()
                        else "absent (importe l'etat via migrer.py)"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gpu', action='store_true')
    ap.add_argument('--cpu', action='store_true')
    ap.add_argument('--prewarm', action='store_true')
    ap.add_argument('--autostart', action='store_true')
    ap.add_argument('--no-ollama', action='store_true')
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()

    if args.check:
        doctor()
        return 0

    print("== Installation MediaLibrary ==")
    if not etape_python():
        return 1
    gpu = args.gpu or (not args.cpu and gpu_present())
    say(OK if gpu else WARN, f"moteur choisi : {'GPU (CUDA)' if gpu else 'CPU'}")
    if not etape_venv():
        return 1
    etape_deps(gpu)
    etape_ollama(args.no_ollama)
    etape_config()
    if args.prewarm:
        etape_prewarm()
    if args.autostart:
        etape_autostart()
    doctor()

    echecs = [m for s, m in _report if s == KO]
    print("\n== " + ("TOUT EST PRET" if not echecs
                     else f"{len(echecs)} point(s) a regler") + " ==")
    if echecs:
        for m in echecs:
            print("  - " + m)
    print("\nEnsuite : importe l'etat (python migrer.py importer <archive>) si "
          "nouveau PC, puis lance « 0 - Démarrer le serveur.bat ».")
    return 0


if __name__ == '__main__':
    sys.exit(main())
