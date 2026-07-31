@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ================================================
echo  Activer le GPU pour les visages (PyTorch CUDA 13)
echo ================================================
echo.
echo  Installe PyTorch build CUDA 13 (~2,5 Go) dans le .venv.
echo  Il fournit les DLL CUDA + cuDNN qu'onnxruntime reutilise.
echo  (Ne remplace pas Ollama ; sert uniquement aux visages.)
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERREUR : lance d'abord "7 - Installer reconnaissance visages.bat".
    pause
    exit /b 1
)

echo --- Installation de torch (CUDA 13.0) ---
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check torch --index-url https://download.pytorch.org/whl/cu130
if errorlevel 1 (
    echo.
    echo Premiere tentative echouee. Nouvel essai avec extra-index-url...
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check torch --extra-index-url https://download.pytorch.org/whl/cu130
)
if errorlevel 1 (
    echo.
    echo ERREUR : torch CUDA 13 n'a pas pu s'installer.
    echo Verifie ta connexion, ou reste sur CPU (tout fonctionne deja).
    pause
    exit /b 1
)

echo.
echo ================================================
echo  Verification : CUDA vu par PyTorch et onnxruntime
echo ================================================
".venv\Scripts\python.exe" -c "import torch; print('torch CUDA dispo :', torch.cuda.is_available()); print('GPU :', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'aucun')"
".venv\Scripts\python.exe" -c "import onnxruntime as ort; ort.preload_dlls() if hasattr(ort,'preload_dlls') else None; print('Providers ONNX :', ort.get_available_providers())"

echo.
echo  Si 'torch CUDA dispo : True' et 'CUDAExecutionProvider' apparaissent,
echo  le GPU est pret. Relance "Demarrer le serveur.bat".
echo  Les visages basculeront sur GPU quand la VRAM est libre (Ollama au repos),
echo  et resteront sur CPU sinon - le tagging garde la priorite.
echo.
pause
