"""
Reparation de la configuration GPU du projet.
──────────────────────────────────────────────────────────────────────────────

DIAGNOSTIC ETABLI
    torch installe = build CPU (2.13.0+cpu, torch.version.cuda = None), et un
    dossier orphelin « ~orch » traine dans le venv. Ce prefixe « ~ » est la
    marque d'une desinstallation pip INTERROMPUE : pip renomme un paquet qu'il
    n'arrive pas a supprimer parce que ses fichiers sont verrouilles — ce qui
    arrive quand le serveur tourne encore et a deja charge torch.

    Consequence : YOLO, DINOv2 et InsightFace tournent tous sur CPU, et les
    seuils *_GPU_MIN_FREE_MB n'ont aucun effet. Seul Ollama utilise la carte.

POURQUOI « 8 - Activer GPU (PyTorch CUDA).bat » N'A PAS SUFFI
    Il installe « torch » SEUL. Or torchvision, timm et ultralytics dependent
    de torch : a la premiere occasion, le resolveur de pip reinstalle un torch
    compatible depuis PyPI — c'est-a-dire la build CPU. Il faut installer torch
    ET torchvision ensemble depuis l'index CUDA pour que la resolution soit
    coherente.

USAGE
    python reparer_gpu.py --diagnostic
    python reparer_gpu.py --nettoyer      # supprime les dossiers orphelins ~*
    python reparer_gpu.py --verifier      # controle complet apres installation
    python reparer_gpu.py --restaurer-cpu # retour arriere
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
VENV = SCRIPT_DIR / ".venv"
PY = VENV / "Scripts" / "python.exe"
SITE = VENV / "Lib" / "site-packages"
INDEX_CU = "https://download.pytorch.org/whl/cu130"


def python_venv():
    return str(PY) if PY.exists() else sys.executable


def sonde(code):
    """Execute un fragment Python dans le venv et renvoie sa sortie."""
    try:
        r = subprocess.run([python_venv(), "-c", code], capture_output=True,
                           text=True, timeout=180)
        return (r.stdout or r.stderr).strip()
    except Exception as e:                                   # noqa: BLE001
        return f"(echec : {e})"


def orphelins():
    """Dossiers « ~xxx » laisses par une desinstallation pip interrompue."""
    if not SITE.exists():
        return []
    return sorted(p for p in SITE.iterdir() if p.name.startswith('~'))


def taille(p):
    total = 0
    for racine, _, fichiers in os.walk(p):
        for f in fichiers:
            try:
                total += (Path(racine) / f).stat().st_size
            except OSError:
                pass
    return total


def diagnostic():
    print("=" * 70)
    print("  DIAGNOSTIC GPU")
    print("=" * 70)

    print("\n  1) PyTorch")
    print("     " + sonde(
        "import torch;print('version =', torch.__version__);"
        "print('     torch.version.cuda =', torch.version.cuda);"
        "print('     cuda disponible =', torch.cuda.is_available());"
        "print('     GPU =', torch.cuda.get_device_name(0) "
        "if torch.cuda.is_available() else 'aucun')").replace("\n", "\n     "))

    print("\n  2) onnxruntime")
    print("     " + sonde(
        "import onnxruntime as ort\n"
        "try:\n ort.preload_dlls()\nexcept Exception as e:\n print('preload:', e)\n"
        "print('providers =', ort.get_available_providers())"
    ).replace("\n", "\n     "))

    print("\n  3) DLL CUDA disponibles dans le venv")
    trouves = []
    for motif in ("nvidia/**/bin/*.dll", "torch/lib/*.dll"):
        for p in SITE.glob(motif):
            if any(n in p.name.lower() for n in ("cublas", "cudnn", "cudart")):
                trouves.append(p)
    if trouves:
        for p in trouves[:6]:
            print(f"     {p.relative_to(SITE)}")
        if len(trouves) > 6:
            print(f"     ... et {len(trouves)-6} autres")
    else:
        print("     aucune -> c'est la cause des erreurs 'cublasLt64_13.dll'")

    print("\n  4) Dossiers orphelins (desinstallation pip interrompue)")
    orph = orphelins()
    if orph:
        for p in orph:
            print(f"     {p.name}  ({taille(p)/1048576:.0f} Mo)  <- a supprimer")
    else:
        print("     aucun")

    print("\n  5) Espace disque")
    try:
        libre = shutil.disk_usage(SCRIPT_DIR).free / 1073741824
        print(f"     {libre:.1f} Go libres  "
              f"({'suffisant' if libre > 6 else 'INSUFFISANT : il faut ~6 Go'})")
    except OSError as e:
        print(f"     indeterminable : {e}")
    print()
    return 0


def nettoyer():
    print("=" * 70)
    print("  NETTOYAGE DES ORPHELINS")
    print("=" * 70)
    orph = orphelins()
    if not orph:
        print("  Aucun dossier orphelin.")
        return 0
    for p in orph:
        mo = taille(p) / 1048576
        try:
            shutil.rmtree(p)
            print(f"  + {p.name} supprime ({mo:.0f} Mo liberes)")
        except OSError as e:
            print(f"  x {p.name} : {e}")
            print("    Un processus tient encore ces fichiers.")
            print("    Arrete le serveur ET ferme tout terminal Python, puis")
            print("    relance ce script.")
            return 1
    print()
    return 0


def installer():
    print("=" * 70)
    print("  INSTALLATION DE TORCH CUDA 13")
    print("=" * 70)
    print("  Environ 2,5 Go de telechargement. torch ET torchvision sont")
    print("  installes ENSEMBLE : sinon le resolveur de pip reinstalle un")
    print("  torch CPU depuis PyPI pour satisfaire torchvision.")
    print()
    base = [python_venv(), "-m", "pip", "install", "--disable-pip-version-check",
            "--upgrade", "--force-reinstall", "torch", "torchvision"]
    for drapeau in ("--index-url", "--extra-index-url"):
        cmd = base + [drapeau, INDEX_CU]
        print(f"  $ pip install ... {drapeau} {INDEX_CU}")
        if subprocess.run(cmd).returncode == 0:
            return 0
        print(f"\n  Echec avec {drapeau}. Nouvelle tentative...\n")
    print("  x Installation impossible. Ton environnement reste fonctionnel")
    print("    en CPU. Verifie ta connexion, puis relance.")
    return 1


def verifier():
    print("=" * 70)
    print("  VERIFICATION")
    print("=" * 70)
    ok = True

    sortie = sonde("import torch;"
                   "print(torch.__version__, torch.version.cuda, torch.cuda.is_available())")
    print(f"\n  torch : {sortie}")
    if 'True' not in sortie:
        print("  x PyTorch ne voit pas le GPU.")
        ok = False
    else:
        print("  + PyTorch voit le GPU")

    sortie = sonde("import torch, onnxruntime as ort\n"
                   "try:\n ort.preload_dlls()\nexcept Exception:\n pass\n"
                   "print(ort.get_available_providers())")
    print(f"\n  onnxruntime : {sortie}")
    if 'CUDAExecutionProvider' not in sortie:
        print("  x onnxruntime n'expose pas CUDAExecutionProvider.")
        ok = False
    else:
        print("  + onnxruntime expose CUDAExecutionProvider")

    print("\n  Test reel : session InsightFace sur GPU")
    sortie = sonde(
        "import torch, onnxruntime as ort\n"
        "try:\n ort.preload_dlls()\nexcept Exception:\n pass\n"
        "from insightface.app import FaceAnalysis\n"
        "a=FaceAnalysis(name='buffalo_l',"
        " providers=['CUDAExecutionProvider','CPUExecutionProvider'],"
        " allowed_modules=['detection','recognition'])\n"
        "a.prepare(ctx_id=0, det_size=(640,640))\n"
        "print(a.models['detection'].session.get_providers())")
    derniere = [l for l in sortie.splitlines() if l.strip()][-1:] or ['(vide)']
    print(f"  {derniere[0]}")
    if 'CUDAExecutionProvider' in derniere[0]:
        print("  + InsightFace tourne reellement sur GPU")
    else:
        print("  ! InsightFace est reste sur CPU.")
        print("    Normal si Ollama occupe la VRAM a cet instant (4 Go seulement).")
        print("    Arrete Ollama et relance --verifier pour trancher.")

    print("\n  VRAM")
    print("  " + sonde(
        "import torch\n"
        "if torch.cuda.is_available():\n"
        "    libre, total = torch.cuda.mem_get_info()\n"
        "    print(f'{libre/1048576:.0f} Mo libres sur {total/1048576:.0f} Mo')\n"
        "else:\n    print('indisponible')"))

    print()
    print("=" * 70)
    if ok:
        print("  + GPU OPERATIONNEL")
        print("=" * 70)
        print("  Relance le serveur. Les visages, YOLO et DINOv2 basculeront")
        print("  sur GPU quand la VRAM est libre, et resteront sur CPU sinon :")
        print("  le tagging Ollama garde la priorite.")
    else:
        print("  x GPU NON OPERATIONNEL")
        print("=" * 70)
        print("  Tout continue de fonctionner en CPU. Pour revenir a l'etat")
        print("  d'origine : python reparer_gpu.py --restaurer-cpu")
    print()
    return 0 if ok else 1


def restaurer_cpu():
    print("  Retour a la build CPU de PyTorch...")
    r = subprocess.run([python_venv(), "-m", "pip", "install",
                        "--disable-pip-version-check", "--upgrade",
                        "--force-reinstall", "torch", "torchvision"])
    print("  + Restaure." if r.returncode == 0 else "  x Echec.")
    return r.returncode


def main():
    args = set(sys.argv[1:])
    if not PY.exists():
        print(f"  ! Environnement virtuel introuvable : {PY}")
        print("    Lance d'abord \"7 - Installer reconnaissance visages.bat\".")
        return 1
    if '--diagnostic' in args:
        return diagnostic()
    if '--nettoyer' in args:
        return nettoyer()
    if '--installer' in args:
        return installer()
    if '--verifier' in args:
        return verifier()
    if '--restaurer-cpu' in args:
        return restaurer_cpu()
    return diagnostic()


if __name__ == '__main__':
    sys.exit(main())
