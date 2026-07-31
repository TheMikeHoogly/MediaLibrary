@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ================================================
echo  Nommage des chats - Phase 2 (embeddings DINOv2)
echo  Installation des dependances (dans .venv)
echo ================================================
echo.
echo  Paquet : timm (fournit DINOv2 pour differencier les chats).
echo  Necessite torch, deja installe par la Phase 1 (ultralytics).
echo  Le modele DINOv2 se telecharge au 1er calcul d'embedding.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERREUR : environnement .venv introuvable.
    echo Lance d'abord "9 - Installer reconnaissance animaux.bat".
    pause
    exit /b 1
)

echo --- Mise a jour de pip ---
".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check --upgrade pip

echo --- Installation timm ---
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check timm
if errorlevel 1 (
    echo ERREUR : timm n'a pas pu s'installer.
    pause
    exit /b 1
)

echo.
echo ================================================
echo  Verification
echo ================================================
".venv\Scripts\python.exe" -c "import timm; print('timm', timm.__version__, 'OK')"

echo.
echo  Termine. Relance ensuite "Demarrer le serveur.bat".
echo  Ouvre la page Chats : http://localhost:PORT/pets
echo  (les embeddings se calculent en fond quand la machine est au calme).
echo.
pause
