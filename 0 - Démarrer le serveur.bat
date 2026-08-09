@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM === Arreter toute ancienne session du serveur avant de relancer ===
set "PORT=8080"
echo Arret des anciennes sessions du serveur sur le port %PORT%...
for /f "tokens=5" %%P in ('netstat -ano -p TCP ^| findstr /C:":%PORT% " ^| findstr "LISTENING"') do (
    echo   Processus %%P arrete.
    taskkill /F /PID %%P >nul 2>&1
)

REM === Environnement Python isole - cree une seule fois ===
if not exist ".venv\Scripts\python.exe" (
    echo Creation de l'environnement Python isole - une seule fois...
    python -m venv .venv
)

echo Verification des dependances pillow, pillow-heif, piexif...
".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check pillow pillow-heif piexif

REM === Lancer le serveur dans une FENETRE SEPAREE ===
echo Demarrage du serveur dans une nouvelle fenetre...
start "MediaLibrary - Serveur" ".venv\Scripts\python.exe" server.py

echo.
echo Serveur lance sur le port %PORT%. Cette fenetre va se fermer.
timeout /t 3 >nul
