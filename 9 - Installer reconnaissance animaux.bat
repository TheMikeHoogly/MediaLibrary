@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ================================================
echo  Reconnaissance des animaux - Phase 1 (detection)
echo  Installation des dependances (dans .venv)
echo ================================================
echo.
echo  Paquet : ultralytics (YOLO). Detecte chats, chiens, oiseaux...
echo  Les poids yolo11n.pt se telechargent au 1er lancement du serveur.
echo  Le nommage individuel des chats (Caline, Inti, Luna) viendra en Phase 2.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Creation de l'environnement Python isole - une seule fois...
    python -m venv .venv
)

echo --- Mise a jour de pip ---
".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check --upgrade pip

echo --- Installation ultralytics (YOLO) ---
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check ultralytics
if errorlevel 1 (
    echo ERREUR : ultralytics n'a pas pu s'installer.
    pause
    exit /b 1
)

echo.
echo ================================================
echo  Verification du moteur YOLO
echo ================================================
".venv\Scripts\python.exe" -c "from ultralytics import YOLO; print('Ultralytics OK'); import torch; print('CUDA dispo :', torch.cuda.is_available())"

echo.
echo  La detection tourne sur CPU par defaut (ne gene pas le tagging GPU).
echo  Pour tester le GPU : passer ANIMAL_DEVICE = \"cuda\" dans server.py.
echo.
echo  Termine. Relance ensuite "Demarrer le serveur.bat".
echo  Verifie la detection avec l'URL : http://localhost:PORT/api/animals/status
echo.
pause
