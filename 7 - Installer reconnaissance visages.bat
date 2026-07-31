@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ================================================
echo  Reconnaissance de personnes - Phase 1
echo  Installation des dependances (dans .venv)
echo ================================================
echo.
echo  Paquets : insightface, onnxruntime-gpu, numpy, opencv, psutil
echo  Le modele buffalo_l se telecharge au 1er lancement du serveur.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Creation de l'environnement Python isole - une seule fois...
    python -m venv .venv
)

echo --- Mise a jour de pip ---
".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check --upgrade pip

echo --- Sonde materielle (psutil) ---
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check psutil

echo --- Installation numpy + onnxruntime-gpu ---
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check numpy onnxruntime-gpu
if errorlevel 1 (
    echo.
    echo ATTENTION : onnxruntime-gpu n'a pas pu s'installer.
    echo Repli sur onnxruntime CPU - plus lent mais fonctionnel.
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check onnxruntime
)

echo --- Installation insightface ---
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check insightface
if errorlevel 1 (
    echo ERREUR : insightface n'a pas pu s'installer.
    pause
    exit /b 1
)

echo.
echo ================================================
echo  Verification du moteur GPU ou CPU
echo ================================================
".venv\Scripts\python.exe" -c "import onnxruntime as ort; print('Providers ONNX :', ort.get_available_providers())"

echo.
echo  Pour le GPU : onnxruntime-gpu exige CUDA + cuDNN installes.
echo  Si CUDAExecutionProvider n'apparait pas ci-dessus, le CPU sera utilise.
echo.
echo  Termine. Relance ensuite "Demarrer le serveur.bat",
echo  puis ouvre la page Visages pour verifier la detection.
echo.
pause
