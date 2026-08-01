@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
echo ==============================================================
echo   INSTALLATION MEDIALIBRARY - nouveau PC
echo ==============================================================
echo.
echo   Reconstruit l'environnement (.venv), les dependances IA, le
echo   modele Ollama et la config. Idempotent : relancable sans risque.
echo   Le GPU est detecte automatiquement (build CUDA), sinon CPU.
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo   Python introuvable. Installe-le d'abord :
    echo     winget install Python.Python.3.12
    echo   puis rouvre une fenetre et relance ce script.
    pause
    exit /b 1
)

set "FLAGS="

echo.
choice /c ON /n /m "Pre-telecharger les modeles IA maintenant (plus long) ? [O/N] : "
if not errorlevel 2 set "FLAGS=%FLAGS% --prewarm"

echo.
choice /c ON /n /m "Lancer le serveur automatiquement a l'ouverture de session ? [O/N] : "
if not errorlevel 2 set "FLAGS=%FLAGS% --autostart"

echo.
echo   Installation en cours...
echo --------------------------------------------------------------
python installer.py %FLAGS%

echo.
echo   Si tu migres depuis un ancien PC, importe maintenant son etat :
echo     python migrer.py importer "chemin\vers\migration_XXXX.zip"
echo   Puis lance le raccourci "0 - Demarrer le serveur" (bat).
echo.
pause
